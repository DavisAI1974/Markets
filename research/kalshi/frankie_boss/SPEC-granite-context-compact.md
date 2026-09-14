# Exact compact native critic context

Add a separate compact context, prompt and parser identity. Native V1 remains
unchanged and is the inverse authority. The codec consumes validated V1, removes
only derived field_paths/scalar_views, and interns identical typed subtrees in
deterministic postorder. Ordered dictionary key shapes are shared. Homogeneous
primitive vectors retain inline typed values; QSV names, identical vectors and
masks are shared, never approximately matched. Masked values remain present.

Finite float64 uses canonical Python repr with verified IEEE roundtrip. Other
IEEE patterns retain bit hex. Bytes retain hex. Null, absent, bool, int, float,
list, tuple, dictionary order and graph rows remain distinct. Derived logical
paths use the existing row plus JSON Pointer convention, including every QSV
name. No opaque compression, reduction, truncation, aggregation or omitted row.

Decode recovers byte-identical V1 text, validates V1 input/packet/tensor bindings,
and re-encodes to require exact compact canonicality: no aliases, unreachable or
duplicate nodes, forward references or alternate scalar spellings. The compact
envelope binds V1 hash; critic output must instead bind the compact snapshot hash.
Prompt and parser have independent pins. Shared service routing is a later explicit
opt-in integration and cannot silently substitute this representation for V1.

Tests cover inverse bytes/tensors, exact primitive distinctions, shared/differing
vectors, tampering, logical references and independent identities. Capacity uses
the pinned IBM tokenizer and exact chat template on the existing synthetic
1/32/128/512-row fixture construction. Repeated zero-QSV measurements do not
establish capacity for unique vectors or 4096 rows. Arbitrary 4096x64 float64
values alone contain 2 MiB before masks and market evidence, so no guaranteed
full-window fit is claimed.
Raw and adapter names remain literal; undeclared units/price scales stay unknown.
Inverse and capacity tests do not establish Granite's semantic comprehension.

Decoder resource admission is explicit through `DecodeLimits`: default maximum
depth 64, four million logically expanded nodes, 256 MiB conservative expanded
encoded-byte accounting, and 64 MiB input text. Backward-reference costs are
computed once per table node before recursive canonical re-encoding, so a tiny
doubling DAG cannot trigger exponential work. Oversize input raises; nothing is
truncated or omitted. Callers may select different positive budgets explicitly.
These operational budgets do not enter context/prompt bytes or claim model token
capacity. Tests preserve exact inverse for 5,000 distinct vectors and reject
doubling, deep nesting and repeated large text through the public parser before
the recursive encoder runs.

## Measured synthetic capacity

Exact original V1 control prompt hashes matched all eight original records in
work/granite-tokenizer/capacity.json. Same measure_granite_context.py fixture
construction, 1/32/128/512 rows only, separate compact-context-N scratch folders;
replace prompt construction with build_compact_prompt(compact_native_context(state)).
The tokenizer uses add_special_tokens=False after the unchanged chat template
renders one user message, enable_thinking=False, add_generation_prompt=True.

| Rows | V1 without QSV | Compact without QSV | V1 with QSV | Compact with QSV |
| --- | ---: | ---: | ---: | ---: |
| 1 | 3483 | 2241 | 5744 | 3064 |
| 32 | 50733 | 7445 | 122335 | 8326 |
| 128 | 197186 | 23626 | 483555 | 24847 |
| 512 | 783485 | 92932 | 1928858 | 95301 |

Counts include the rendered chat prompt, exclude generated response tokens.
QSV fixture is repeated all-zero vectors with all-true masks. These savings
depend on exact repetition and do not predict unique-vector capacity.
No 4096-row measurement or deployed service acceptance is asserted.

Tokenizer SHA256: 883975314d58743726347caaf2c32ac89afd5ad57222cffbc4f052f2ab27b2d7.
Chat template SHA256: f0ba43f79b3cabca5e5a7584c77aec92f49feae45cdf7779c87d9fc54cd90258.
Per-case prompt, rendered text and native snapshot hashes are retained in
work/granite-tokenizer/capacity-compact.json. At 512 rows with QSV the compact
prompt SHA256 is 93f1f3a323248dc3eb8c0ca0079127c9ca261699994395a1337d2803e43f630c.
