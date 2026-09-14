# Committed BOSS attachment receiver

The agent lineage consumes `BOSS_AGENT_FILE_HANDOFF_V1` exports from the separately
committed BOSS producer. The independent manifest SHA256 authenticates the
producer's semantic journal verification. This receiver does not import BOSS or
reimplement its C15, forecast, or Granite semantics.

`native_boss_attachment.AttachmentRequest` is coordinator configuration. Both
existing commands accept `--boss-attachment-request path.json`; its JSON keys
are exactly the dataclass fields. Paths resolve relative to the configuration
file. Pins must be obtained through the coordinator's trusted handoff, not copied
from an untrusted export during verification. There is no automatic pin inference.

Required fields: `directory`, `expected_manifest_sha256`, `expected_boss_commit`,
`expected_agent_commit`, `controller_checkpoint`, `native_checkpoint`,
`crosswalk_path`, `expected_crosswalk_sha256`, `mapping_artifact`, `mode`.
The two checkpoint schemas are `BOSS_FRANKIE_CONTROLLER_JOURNAL_V1` and
`BOSS_ROLLING_FORECAST_V1`. Complete attachments require every ordered target
(`instrument`, `target_id`, `target_ns`), revision >= 1, its exact record/artifact,
state, both full journals, and both critic text files. Files, names, purposes,
lengths, hashes, exact directory membership and canonical manifest bytes are
checked. Links, extra files, missing files and incomplete statuses are refused.

The default receiver verifies its executing Git HEAD, refuses staged/unstaged
research changes and untracked research files, then compares the independently
expected agent commit. Packaged in-process deployments can pass an independently
trusted committed-build identity directly to `verify_attachment`; this override
is deliberately absent from the request-file/CLI interface. Ordinary emit/read-back
always use the executing checkout identity.

Operationally, keep this code checkout clean and frozen at the manifest's exact
`agent_commit` for both emission and read-back. Commit the delivered ledgers,
prompt, agent-authored outputs and receipts in a separate evidence worktree/branch,
and pass their external paths to these existing commands. Record that evidence
commit separately. Committing evidence must not move the frozen code checkout's
HEAD or relabel its build identity. There is no arbitrary-ancestor exception.

## Source-binding attestation

`crosswalk_path` contains canonical UTF-8 JSON with sorted keys, compact separators,
ASCII escapes, no NaN and no trailing newline. Its independently supplied SHA256
pins these exact fields:

- `schema`: `FRANKIE_BOSS_SOURCE_BINDING_V1`.
- `boss_source`: the entire BOSS source object, including prefix hash, cursor,
  source/evaluation cutoffs and arm hash.
- `agent`: `run_id`, `arm`, `source_day`, `source_manifest_hash`,
  `delivery_manifest_sha256`, `delivery_receipt_sha256`, `result_hash`.
- `provenance`: nonempty `authority`, `method`, `mapping_artifact_sha256` and
  `mapping_artifact_bytes`.

The mapping artifact must exist, be nonempty, and match both byte witnesses.
The actual delivered calculation result, its self-hash, source identity and single
source day must match the attestation. Its delivery receipt must match the actual
result bytes and all three plaintext ledgers, which are freshly hashed through the
existing delivery verifier. Different hash domains remain distinct.

This is **caller-attested source mapping with retained byte evidence**, not
independently proven raw-to-BOSS semantic equivalence. The receipt names that
qualification, authority, method and artifact witness. The mapper's claims must
be reviewed independently; the receiver cannot manufacture missing mapping
evidence from timestamps, filenames or counts. No operational mapping artifact
has been established by the synthetic tests.

## Explicit exposure and admission

`attributed_input` appends a clearly attributed BOSS/Granite block to the existing
emitted prompt. All original attachment, manifest, mapping and attestation bytes
are preserved as base64 within the actual serialized prompt. Producer text is
evidence rather than instructions. Frankie must cite the attachment receipt in
`boss_attachment_receipt_sha256` on his own artifact. The producer guarantees the
entire archive is causal at the selected request; its last-result/export checks
prevent a later request or candidate from leaking through historical journals.

`post_agent_comparison` is supplied only to read-back. Emit refuses that mode.
Read-back refuses the attributed-input marker or citation in this mode. This
mechanically checks the supported serialization path; it cannot prove the agent
was never exposed through a separate, unrecorded channel.

The existing default prompt and read-back behavior remain unchanged without an
attachment request. Integrated read-back first admits actual principal findings,
full output bundle and complete/drained delivery/stream receipts through existing
validators. It additionally requires exact staged prompt/bundle bytes and the
existing knowledge-use gate even if an in-process caller supplied a custom legacy
hook. Pre-input mode requires the exact block and citation. Refusal occurs before
any result or handoff write.

Successful read-back writes a separate `<result_with_findings>.boss.json` record
with exclusive creation. It links the attachment receipt, principal artifact,
original and attached result hashes, outputs/delivery/stream/knowledge receipts,
knowledge-use receipt, and exact serialized principal input SHA256/length. It
neither creates findings nor writes memory. Previous result, handoff and combined
paths are never overwritten.

## Frozen producer fixture and verification

`tests/fixtures/boss_handoff_8a79d775.zip` contains the exact synthetic export from
BOSS producer commit `8a79d775` (full commit in its manifest), three targets, fake
critic transport and zero provider calls. The declared receiver identity is
`9999999999999999999999999999999999999999`, used only as a trusted synthetic
packaged-build fixture. Archive SHA256:
`c6215567324ed7d8a586a163448c6d13268d7a83847d9b457c860048d80639ab`.
Manifest SHA256:
`aee433b0d0251bb2519403a83c92d55b512d43f5d71914413a3b419144703044`.

Focused receiver and existing emitter/staging/handoff/stream suites: 247 passed;
the subsequent tracked-module and same-test emit-to-read-back checks pass in the
45-test receiver suite.
Tests cover both modes, all physical pins, actual ledger changes, source/day/arm/
cursor mismatch, links, malformed manifests, committed-source refusal, existing
combined paths, and incomplete knowledge/input/consumption. No principal session,
replay, provider call or trading action was performed by this implementation.

Windows validation requires the exact knowledge-manifest-pinned artifact bytes.
The new worktree initially applied CRLF conversion; the test setup was corrected
by restoring those files from verified HEAD blob bytes. Manifest hashes and
historical knowledge were not changed.
