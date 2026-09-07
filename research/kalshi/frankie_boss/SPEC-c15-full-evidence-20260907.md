# C15 evidence and teacher contract — corrected 2026-09-07

Authority: CLAUDE_TO_CODEX_FULL_EVIDENCE_RULING_20260907.md, approved by Greg.

C15_FULL_EVIDENCE_V1 remains the append-only evidence of record: every raw
submission precedes processing; all successful events, non-F_LAST rows, failures,
orders, source members, sessions, resets and exact field values are retained.
Nothing is capped or averaged in this evidence path. Frankie inputs, calculations,
planes, adapters, replay, Memory A and BLD-1 remain protected.

BOSS_TEACHER_CANDIDATE_C15R2 is reinstated as the downstream 19-column teacher
contract. c15_normalizer.py and c15_dstate.py are current teacher components,
not retired research. The six unbuilt B2/C1 slots remain ABLATED. Their absence
is explicit and does not suppress the corresponding native evidence inputs.
Candidate equations, 64/1024 group horizons, exclusive 4096-observation target
normalizer, warmup, floors and clipping follow R2 and the R3 addendum sections
3/4. They transform teacher targets only; original raw evidence remains complete.
The target builder reads complete journal history, with each row accounted for,
and emits raw and normalized candidate values with states at matching cutoffs.

BOSS_TRUNK_V2 restores window=128 and use_qsv=False; window=None and QSV are
explicit experiment choices. B0 is pinned at beb548b8. Granite output/prompt V1
caps return; state serialization V2 and lowercase hashes remain. The withdrawn
FullHistoryRunner is replaced by ContextSessionRunner; its declared context is
not an evidence retention limit. See SPEC-native-mbo-encoder.md for exact mapping
and receipt semantics. No production integration, training, provider, market
run, mechanics probe or OSS evaluation is authorized here.
