## Notes on part 1/9 (bytes 0-139295) [OUTPUT INCOMPLETE]

**NOTES for merge (part 1/9 of delivered evidence, cycle 00, pin = legacy_observable_crosswalk)**  

*Only observed facts with exact numbers, hashes and section ids as they appear are recorded. No inference is presented as fact. Distinguish observed vs inferred. No numbers or hashes are invented. Markdown ≤ 1200 words.*

---

### 1. Observed facts with exact numbers, hashes and section ids as they appear

*(All identifiers, hashes, timestamps and numeric values are copied verbatim from the text; no interpretation added.)*

- **Sunday 2021-10-03 is the sole source and run day. No separate source day or October 1 prerequisite applies.** (sentence in “Current authorized continuation”)
- **Reuse completed principal-authored sections with their original authorship; author the new source convention, BOSS feedback and run analysis. Preserve frozen pre-Sunday Memory A; store new lessons separately.** (same sentence)
- **Actual local delivery:** `C:\Codex\Frankie-BOSS-20260919\retained-principal\delivery_receipt.json` (exact path)
- **Feedback contract:** JSON object with fields  
  `"as_of":1633298413318097271`,  
  `"contract_sha256":"359e369cbc43b48ef33280dc64a44200e53d1d3612ed1e10fe26988e7e2baefd"`,  
  `"cycle_index":0`,  
  `"development_units":"Explicit development numeraire; actual NG contract multiplier unidentified in supplied MBO metadata."`,  
  `"expected_sessions_hash":"b3424ec47d636ca40c0847c730c8b823f33a16768b594961455aa8fca802c721"`,  
  `"learning_cutoff_ns":1633298449136124134`,  
  `"learning_through_source_cursor":6053`,  
  `"path_query_offsets_ns":[1082905384677,1477831169583,4044058116079,4819012459037,6137430285344,6537240678811,6943744850312,7114039682715]`,  
  `"query_policy_hash":"1d7ab931595fd7df8617073afd8e11536f0ff452c0801a5964791086c7381642"`.
- **Sessions array contains one session** with key `"session"` and fields:  
  `"calendar_hash":"4046617ff4746233d6d19216178517c957b102e6a5fcd645313194c154210749"`,  
  `"close_ns":1633305600000000000`,  
  `"convention_hash":"e9b813753d2ef4c9eb2497aef86288c23fbaee57bea53fb46ef32b382990004f"`,  
  `"event_cutoff_ns":1633298413317923251`,  
  `"instrument":"NG.v.0/instrument_id=111313"`,  
  `"knot_policy":{"max_interior":57027,"quantum_ns":1}`,  
  `"known_marks"` list (see below), `"open_ns":1633298400329344207`, `"opening"` object, `"receive_cutoff_ns":1633298413318097271`, `"session_id":"NG_111313_OWN_SOURCE_20211003"`, `"source_hash":"e947260436b02edcc4d3214499956442c5d1951756298eddf3e448631861e2b5"`, `"tick_size":0.001`, `"usd_per_price_unit":1.0`, `"target"` object.
- **`known_marks` list** (exact entries as they appear; each has `"event_ns"`, `"evidence_hash"`, `"price"`, `"receive_ns"`):  
  1. `"event_ns":1633298400337726077,"evidence_hash":"05cecdad5be51bc1cfbb42c25a7fbc675450a601c23f9903ae5216ad34774daf","price":5.634,"receive_ns":1633298400450870841`  
  2. `"event_ns":1633298400356107175,"evidence_hash":"e3c89089708039fd4f1ec64828e4506cd96fff7bd87d232a7a28f695ccf8d954","price":5.634,"receive_ns":1633298400453750655`  
  3. `"event_ns":1633298400448278649,"evidence_hash":"cf54e425a2ae87eff0807e6af14685e0461852cb5f5457474513021624d80c27","price":5.634,"receive_ns":1633298400476838678`  
  4. `"event_ns":1633298400462214863,"evidence_hash":"11493686203da84ee600c16667108bf61a00344f69d22586c804c4c4d8dd5c8c","price":5.635,"receive_ns":1633298400483126267`  
  5. `"event_ns":1633298400486059525,"evidence_hash":"284ea7d91142f24a18a3de32a38d38809035869425389fffbd8afb4b1db0f228","price":5.645,"receive_ns":1633298400492544718`  
  6. `"event_ns":1633298400490916177,"evidence_hash":"370a869e580a4cbc66fbbf748508fd19fe003e348ddae40aac5706c88bbd0ae2","price":5.645,"receive_ns":1633298400496059551`  
  7. `"event_ns":1633298400492065759,"evidence_hash":"4e99ad0e0d16c8a4e07a7281ce24cee50ccd3619baa00c06ecd3c120f4e5900c","price":5.645,"receive_ns":1633298400498959019`  
  8. `"event_ns":1633298400497818515,"evidence_hash":"e938d5ca39e5713d9accefd3b9b67980fd465218e97eb465f394ba7b8f8135a6","price":5.648,"receive_ns":1633298400502331621`  
  9. `"event_ns":1633298400497820537,"evidence_hash":"96113dfc134095b8c164f8d32f85ac3960189befb5a516b9844b75ec2a1eeffa","price":5.647,"receive_ns":1633298400503045871`  
  10. `"event_ns":1633298400497838931,"evidence_hash":"add8e456b901f43708eaa76e9f4640f191ff15ffb0f9a11a49a2e389ccf00e70","price":5.647,"receive_ns":1633298400503750376`  
  11. `"event_ns":1633298400497868345,"evidence_hash":"352d8340b38bf7f93afe1999bf03e412b9e71200d5f559fb312c9ac6504c5cf7","price":5.647,"receive_ns":1633298400505529917`  
  12. `"event_ns":1633298400591624925,"evidence_hash":"b18a65bc11de36ca511125c0a1f499d324c9ddbdd78e8ed33fce37554c618785","price":5.644,"receive_ns":1633298400592897437`  
  13. `"event_ns":1633298400592626665,"evidence_hash":"9e8727089da119a1953593eed34dcdcd6f8299369e82673ecd2b367de45474d7","price":5.643,"receive_ns":1633298400596395514`  
  14. `"event_ns":1633298400655649089,"evidence_hash":"71a010ed65e852ef11739959de483fd5a25e973f7029b8b4dde7c05691bd6cf4","price":5.636,"receive_ns":1633298400657498270`  
  15. `"event_ns":1633298400863446851,"evidence_hash":"6d204b4498b9c22e46e368e1296b3abc0c2759be1ec74fb7777bd1d64f07ff6f","price":5.642,"receive_ns":1633298400864486381`  
  16. `"event_ns":1633298400997030249,"evidence_hash":"64196837c6745ca5f8a9aba678cbdb27be28504b54da7669eb6b1ba2c84bbf13","price":5.635,"receive_ns":1633298400997731566`  
  17. `"event_ns":1633298401002641343,"evidence_hash":"294ff546be56e7d20a150fb9dea5dfe1ad718ffc1a8926308cc1082a3d49ab52","price":5.636,"receive_ns":1633298401003985255`  
  18. `"event_ns":1633298401005128159,"evidence_hash":"64a83cb0e6d9c04df5fc39da1be2b777e29f6c01b853857619d4d92bc3d5cd89","price":5.636,"receive_ns":1633298401006560891`  
  19. `"event_ns":1633298401059743131,"evidence_hash":"5bde6829d702325fd252e4a8024de96a162e2dfa5ac529e5c3134b9513ecba2e","price":5.635,"receive_ns":1633298401061069861`  
  20. `"event_ns":1633298401116994397,"evidence_hash":"5b89f5910202522b57215e01cf45c974c29f1ac7714568cd6de09643ed086cf7","price":5.632,"receive_ns":1633298401118237875`  
  21. `"event_ns":1633298402028376231,"evidence_hash":"70e7dd89f339ea99cc9be6d4bb305d3d8823e831f875dd2f509ee114fc900c88","price":5.633,"receive_ns":1633298402029003627`  
  22. `"event_ns":1633298402028458495,"evidence_hash":"725e9600252006dcda0a6203d14009a6868b0c3969c4102c976dd4aa60d4cbff","price":5.633,"receive_ns":1633298402029396183`  
  23. `"event_ns":1633298402029795413,"evidence_hash":"821623a212f4f60b34b8b77f62a70ff5b2da5822f38042b7b9be8c110fc70275","price":5.633,"receive_ns":1633298402030492231`  
  24. `"event_ns":1633298402445769021,"evidence_hash":"cca9efa8518699e2840c218264d8d5fb4bd6020e51ec8ef5b6a0aa210593796d","price":5.632,"receive_ns":1633298402446641251`  
  25. `"event_ns":1633298403762846813,"evidence_hash":"94fba280dac16edbfd6b19bee9a885c86f3cfa9dd59c3acda1228b10d01c71d6","price":5.63,"receive_ns":1633298403763941727`  
  26. `"event_ns":1633298403973704867,"evidence_hash":"d658c73f4b788b59d6384d9159a5835093ea402ba7d7a9207f4764720edb7769","price":5.634,"receive_ns":1633298403974665507`  
  27. `"event_ns":1633298404658388029,"evidence_hash":"a43eef78a7c792aeaebd777f8edaeadcd644a5a39fad9dc1d306f6351174fb0d","price":5.63,"receive_ns":1633298404662052609`  
  28. `"event_ns":1633298404662026563,"evidence_hash":"d82363c48a222ed37ddeec62a8936e8acc5024eb7a80556521225f756be91eb8","price":5.632,"receive_ns":1633298404663825549`  
  29. `"event_ns":1633298404662050883,"evidence_hash":"3cb148a9ac21c63f3e192616f35b4e8f3356f624330ebaa21080a4103e124aa9","price":5.633,"receive_ns":1633298404664551578`  
  30. `"event_ns":1633298404662095607,"evidence_hash":"eb1244a66bd8d03cf38feac02dedf68b5004835f829aa29d69cc902de2e0eea9","price":5.633,"receive_ns":1633298404665942862`  
  31. `"event_ns":1633298404685821973,"evidence_hash":"5032e086c31b71bc59e8c72ad0ef8fb074bf75df28904fd9424286785ed718b1","price":5.633,"receive_ns":1633298404686842441`  
  32. `"event_ns":1633298406565864507,"evidence_hash":"a4c0df54ebba18e867dc57d8151fc74756faa97c4d40e48d774e49d83c8d45af","price":5.636,"receive_ns":1633298406568749450`  
  33. `"event_ns":1633298407173435023,"evidence_hash":"829abf69d38958c03e4026f255e4581511d53e43d5d5d27cfd5a1c32186c3f75","price":5.632,"receive_ns":1633298407174291603`  
  34. `"event_ns":1633298408454300769,"evidence_hash":"68781bc8f6c95c91662693f964ad2e9673be243c56fc4625dbe8c4fa1cea274d","price":5.63,"receive_ns":1633298408455390237`  
  35. `"event_ns":1633298408455494257,"evidence_hash":"86a62f8cd34863c54c120ed877d7a3a0e456bf4cd79debddbb93f9e9eba70698","price":5.63,"receive_ns":1633298408456128299`  
  36. `"event_ns":1633298409010540203,"evidence_hash":"8ded281f30bdc6f89ad3c33e3a748e79a1e6eff57e405547583d219eeec9c25b","price":5.637,"receive_ns":1633298409012106582`  
  37. `"event_ns":1633298409905975531,"evidence_hash":"ebf7aa36e6ea587821e45d25f7bdb216c6f03b99f0eb8826ea3ac290968ed1d8","price":5.632,"receive_ns":1633298409906724743`  
  38. `"event_ns":1633298409905994423,"evidence_hash":"32a08797ce0881728977db519db930f1bf3120bff216e340a1e440f5417bfc4a","price":5.632,"receive_ns":1633298409907054960`  
  39. `"event_ns":1633298411574631499,"evidence_hash":"480b3f4bd3c4f24a390fe182d6b24c4024c3b13c2c8b17cb65ad51c77d84ccd0","price":5.631,"receive_ns":1633298411575540095`  
  40. `"event_ns":1633298412269015127,"evidence_hash":"b830b3ab36395415bef73ed22a76
