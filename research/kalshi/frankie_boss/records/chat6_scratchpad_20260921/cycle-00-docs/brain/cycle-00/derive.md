# Derivation receipt (derive.json: every layer of the pin with its status, producer and sha256)

```json
{
 "adapter_records": 3262,
 "at": 1789998432.5935307,
 "cycle": "00",
 "f_last_groups": 2282,
 "failure_count": 0,
 "failures": [],
 "input_records": 3262,
 "layers": {
  "legacy_book_imbalance": {
   "bytes": 1498902,
   "path": "/opt/frankie-box/session/work/derived/legacy_book_imbalance.json",
   "producer": "V4MboAdapter F_LAST book snapshot + a_memory_member_first_recalculation_20260828.book_values/book_transition",
   "reason": null,
   "sha256": "73939ae61e64787f2008c5fc359f309c35aefe727ed56baf5d8a817ee775a0a7",
   "status": "derived"
  },
  "legacy_native_signed_flow": {
   "bytes": 1378,
   "path": "/opt/frankie-box/session/work/derived/legacy_native_signed_flow.json",
   "producer": "research/kalshi/frankie_raw_mbo_benchmark/native_roll20.py SecondBinner (clock ts_recv)",
   "reason": null,
   "sha256": "515d41d416f724e4d206f9a43986bf69ed6c20a78e0b217369724d5ad8201bb6",
   "status": "derived"
  },
  "legacy_per_second_roll20": {
   "bytes": 1926,
   "path": "/opt/frankie-box/session/work/derived/legacy_per_second_roll20.json",
   "producer": "research/kalshi/frankie_raw_mbo_benchmark/native_roll20.py roll20 (window 20, clock ts_recv)",
   "reason": null,
   "sha256": "eacce1747cf9032e0b2b63a61d8bd18051e5de3c0c38f990b76faaeec7534a6a",
   "status": "derived"
  },
  "legacy_price": {
   "bytes": 494,
   "path": "/opt/frankie-box/session/work/derived/legacy_price.json",
   "producer": "research/ng_exhaustion_mbo_v4_state_adapter_20260820.py (legacy control row projection)",
   "reason": null,
   "sha256": "507d51fe6b75dad32a138b65ef2659efedf48cbd6b7a063e5603b7a29e363b1a",
   "status": "derived"
  },
  "legacy_structure_observables": {
   "bytes": 3276450,
   "path": "/opt/frankie-box/session/work/derived/legacy_structure_observables.json",
   "producer": "a_memory_member_first_recalculation_20260828.describe_structure per F_LAST group (action string, side string, mirror, fill disposition, family candidate)",
   "reason": null,
   "sha256": "c65376c8d0b7a55dae3e2a9592eb1114cd067a92de6c4668d5de053805844bf7",
   "status": "derived"
  }
 },
 "legacy_rows": 1482,
 "pin_group": "legacy_observable_crosswalk",
 "producers": {
  "research/kalshi/frankie_raw_mbo_benchmark/a_memory_member_first_recalculation_20260828.py": {
   "bytes": 41528,
   "path": "/opt/frankie-box/producers/research/kalshi/frankie_raw_mbo_benchmark/a_memory_member_first_recalculation_20260828.py",
   "sha256": "04194df484a69bb8d91a296e67145d34ada1a24ed1cf2aa1b4529565808369bb"
  },
  "research/kalshi/frankie_raw_mbo_benchmark/native_roll20.py": {
   "bytes": 12887,
   "path": "/opt/frankie-box/producers/research/kalshi/frankie_raw_mbo_benchmark/native_roll20.py",
   "sha256": "8e0a8dd6111cf65dfd87ac153f72824c75fe372da55f24a7ea0c278517d58179"
  },
  "research/ng_exhaustion_mbo_v4_state_adapter_20260820.py": {
   "bytes": 41368,
   "path": "/opt/frankie-box/producers/research/ng_exhaustion_mbo_v4_state_adapter_20260820.py",
   "sha256": "4a80e3e4b83867046d318ba97d350c2d7aca22e9d182d98399d01eeacc72d3ce"
  }
 },
 "rows": {
  "bytes": 463036416,
  "count": 6524,
  "format": "C15_JOURNAL_PREFIX_SNAPSHOT_V1",
  "head": "96f2d5818a59bfadf5ca156ae25cfdfcb9c655355227ea0dda6ff6f70897e3f7",
  "head_is_request_source_hash": false,
  "kinds": {
   "APPLIED": 3262,
   "INPUT": 3262
  },
  "layout": "raw",
  "path": "/opt/frankie-box/data/prefix-00.sqlite",
  "sha256": "722512df404c89783e49b577b163c5917764171aa19237e142c52b859f196883"
 },
 "schema": "FRANKIE_BOX_DERIVATION_RECEIPT_V1"
}
```
