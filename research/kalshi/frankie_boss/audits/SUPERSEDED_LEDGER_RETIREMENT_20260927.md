# Superseded member-ledger retirement proposal

Prepared from storage inventory 36327160928 and current terminal descriptor read 36327307198 on 2026-09-27. Greg explicitly approved this exact proposal after ROOT failed from disk exhaustion. Cleanup run 36327746090 FAILED at 14:57:21Z (SSM command 00d2cb24-815f-4aeb-8d91-2048ba862098, job108643664430) with empty stdout/stderr. No deletion result or recovered-space receipt was retrieved; deletion remains unconfirmed. A preceding observer proved that disk exhaustion prevented the SSM document worker from creating its temporary file. Restore access, inspect existing retention intents and exact target paths, and only then retry within the same approval. Compression has not occurred.

The five explicitly listed files total 945,839,361,320 logical bytes (about 946 GB). These are superseded partial-pass outputs, not claims of whole-file byte identity. Retain all other files in those directories, including checkpoints, state, receipts and errors.

- `work/bedrock/recovery-03a70711353a433c989b18074d7baacd/ledgers/exact_member_rows.jsonl` — 312296413348 bytes
- `work/bedrock/recovery-d4b20c8f7e834d7abb1a435ff8199442/ledgers/exact_member_rows.jsonl` — 231083239987 bytes
- `work/bedrock/recovery-7bd18d968a384248b02e58c74f5456c6/ledgers/exact_member_rows.jsonl` — 186271626117 bytes
- `work/bedrock/ledgers/exact_member_rows.jsonl` — 118280552448 bytes
- `work/bedrock/recovery-f13de5640bf549feaae493d8861bfae1/ledgers/exact_member_rows.jsonl` — 97907529420 bytes

Keep the entire current complete generation `recovery-9defa3169f7d46679491da2b1bfbbce2`, all three complete scientific ledgers, original source, current/parent full terminal checkpoints and states, compressed projection ranges, partial publications, and historical section/hash evidence.

Current terminal controller descriptor SHA256: `3cc7e16ce0cfa3e2c5297d98d860c5231e09c747e5f82c2de698d7f41ed26ab4`; finalized 2,032,203 records. Its three closed materialized ledger paths all point into the retained current generation. The corrected ROOT resume verified those ledgers before restoring them in place. `restore_closed` does not reopen prior prefix ledgers. Older partial checkpoints remain historical documents after retirement and must not be selected for recovery; use the retained full terminal checkpoint.

The committed manual maintenance script requires an explicit confirmation literal, verifies the pinned terminal evidence and exact file metadata, and refuses targets open by any process. It records an intent and per-file removal receipts, then unlinks only these five paths. No recursive deletion, ROOT stop/restart, scientific replay, model call or current-ledger rewrite.

The existing workflow's separate maintenance lock admits this one committed script while ROOT holds the execution lock; no new workflow or automated orchestrator is introduced. This is necessary to reclaim space before the pending publication copy. Downstream staging 36326457453 subsequently FAILED at14:55:58Z with empty SSM output; no successful staging receipt exists.

Approval was obtained for this concrete destructive change because the user's original instruction explicitly protected every ledger and checkpoint. The latest discussion requests cleanup of duplicate work; this proposal identifies the exact obsolete bulk files and loss of earlier partial-checkpoint rollback before deletion.

Compression is deferred for these superseded files: preserving them as compressed bulk would consume additional space and I/O while ROOT needs room to publish. Retained final evidence may be archived later after its readers finish, with exact restore verification.
