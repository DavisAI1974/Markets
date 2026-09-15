# Coordinator attachment preparation

`python -m research.kalshi.frankie_raw_mbo_benchmark.prepare_boss_attachment`
requires `--pins-path`, `--expected-pins-sha256`, `--directory`, `--result-path`,
`--delivery-receipt`, `--mapping-artifact`, and `--output-directory`.
All paths name already present local evidence. The output parent must exist; the
new output directory must be outside the executing clean, committed agent checkout.
Keep that checkout HEAD frozen through preparation, emit and read-back. Commit
principal evidence separately and retain its commit identity at admission.

## Independent coordinator record

The canonical JSON record has exactly these fields:

- `schema`: `FRANKIE_BOSS_PREPARATION_PINS_V1`.
- `pin_origin`: nonempty `authority`, `method`, `reference` naming the independent
  review/record from which these pins were obtained.
- `expected_manifest_sha256`, `expected_boss_commit`, `expected_agent_commit`,
  `controller_checkpoint`, `native_checkpoint`: existing receiver pins.
- `boss_source`: exact entire exported source object, independently reviewed.
- `agent`: existing binding identity with actual run ID, arm, single source day,
  source identity hash, delivery manifest file hash, delivery receipt self-hash,
  and result self-hash. These are separate hash domains.
- `provenance`: existing mapping authority, method, SHA256 and byte length.
- `result_file_sha256`, `delivery_file_sha256`: independent plain-file SHA256 pins,
  distinct from the self-hashes in `agent`.
- `mode`: `attributed_input`.

Canonical bytes use sorted keys, compact separators, ASCII escapes, no NaN and no
trailing newline. Supply their SHA256 independently via `--expected-pins-sha256`.
A matching hash checks identity; the command does not establish who is authorized
or certify the truth of a coordinator's assertions. Never construct trusted pins
by copying an unverified export's claims.

## Outputs and limits

The command validates through the unchanged attachment receiver, which freshly
rehashes all delivered ledgers and result bytes and validates commits, checkpoints,
complete attachment inventory, mapping and crosswalk. It then exclusively creates
`source-binding.json`, `attachment-request.json`, and `preparation-receipt.json`.
The receipt retains pin provenance, input/output byte witnesses and the original
attachment receipt. A failed write can leave an incomplete output directory; it
is never overwritten or advertised by a completed receipt. Use a new evidence
location after investigating. Emit/read-back reverify the original files.

Mapping remains `CALLER_ATTESTED_WITH_BYTE_WITNESS`. The mapper must retain real
source manifests, DBN members/hashes/lengths, extraction pin, ordered cursor
relationships, session/arm and causal cutoffs, with independent review. No generic
mapping format or automatic semantic mapper is established by this interface.
The tests are explicitly synthetic and do not supply operational evidence.

Authentic mapping, independent operational pin authority, and an actual admitted
population producer for the eight BLD metadata fields remain missing. Raw-MBO
findings and preparation receipts do not authenticate those population fields.
No Sunday session, new acquisition, training, held-out reveal, venue call or
principal findings are performed by this command.
