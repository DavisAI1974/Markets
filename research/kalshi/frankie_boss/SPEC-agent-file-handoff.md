# BOSS committed-file attachment V1

The producer exports an already durable controller result, without generation,
transport or agent invocation. The receiver is a separate committed agent build.
An attachment is producer evidence, never principal-authored findings.

`manifest.json` is UTF-8 JSON (`ensure_ascii=True`, sorted keys, compact
separators, no NaN, no trailing newline). Its SHA256 is supplied independently
to the receiver. Fields are exactly:

- `schema`: `BOSS_AGENT_FILE_HANDOFF_V1`
- `boss_commit`, `agent_commit`: independently expected full lowercase Git SHA1s
- `request_id`, `request_hash`, `status` (`complete`, `incomplete`, `idle`)
- `controller_checkpoint`, `native_checkpoint`: original schema/count/head_hash
- `configuration_hash`: C15 evidence_hash of retained controller configuration
- `source`: `prefix_hash`, `through_cursor`, `as_of`, `source_as_of`, `arm_hash`
- `targets`: ordered objects containing `target`, `revision`, `publication_hash`,
  `artifact_digest`, `record_digest`, `record_path`, `artifact_path`
- `files`: sorted objects with `path`, `bytes`, `sha256`, `purpose`

Purposes are fixed: `controller_state`, `controller_journal`, `native_journal`,
`critic_snapshot`, `critic_prompt`, `record`, `forecast_artifact`, respectively.

All files are direct children with fixed generated names. Reject directories,
links, extra/missing members, noncanonical manifests and changed byte witnesses.
`state.c15.json` uses canonical C15 `pack` to preserve tuple/bytes/float types.
`controller.c15.jsonl` and `native.c15.jsonl` contain every verified journal
envelope in ordinal order, canonical C15 packed JSON plus LF per entry. Each
original envelope and its hash remains unchanged. `record-000000.json` holds
the original record_json UTF-8 bytes; `forecast-000000.bin` the original native
artifact bytes. Index width is at least six digits, without a roster cap.
When present, `critic-snapshot.txt` and `critic-prompt.txt` preserve original
UTF-8 text. The packed state retains raw response and service receipt too.

Exporter inputs require request ID and independently trusted controller/native
checkpoints. Reopen both journals against those pins; verify every entry and
semantic transition. Cross-check every retained publication, full target roster,
source cutoffs, source prefix, arm and exact original artifact. Export the full
checkpoint histories, including preceding requests; no truncated journal may
claim the original checkpoint. The selected RESULT must be the final controller
entry. Every preceding request/candidate must have source/receive cutoffs (and
controller cursor) no later than this request. Reject later archive evidence;
exporting an older result requires its retained original checkpoint database.
Every candidate in the native history, including unselected candidates and other
targets, must also deserialize to a valid native artifact with matching original
model/source/target/computation receipts and no context cursor beyond this export.
Source journals are not included or asserted to
be the agent's three ledgers. Their identity is a separate crosswalk gate.
Create a new directory exclusively after validation. Never overwrite a previous
export. Incomplete and idle exports retain their status; receiver admission for
integrated evidence requires complete status.

The producer requires its scoped BOSS source tree to be committed and clean,
including untracked files. Retained controller implementation and transport bytes
must belong to that declared commit; naming Git HEAD alone is insufficient.
Commit identities identify code; on-disk runtime/code hashes still retain platform
byte differences and remain independently checked.

The receiver supplies expected manifest SHA256, both commits, both checkpoints,
and a caller-pinned explicit crosswalk. Crosswalk schema and agent run/delivery
identity validation belong to the agent receiver. It must bind the manifest's
entire source object to actual agent run/source-manifest/delivery/result receipts;
it must not identify a source-manifest hash with a BOSS source-prefix hash or
infer mapping from timestamps, filenames or record counts.

Exposure mode is explicit: `attributed_input` or `post_agent_comparison`.
Default existing emit/read_back behavior is unchanged. Pre-agent input must be
serialized into the actual input and labeled BOSS/Granite producer evidence.
Post-agent comparison stays outside principal input and joins only after the
existing principal admission verifies actual output, prompt/bundle and complete
stream/delivery/knowledge witnesses. Neither mode creates findings or memory.
