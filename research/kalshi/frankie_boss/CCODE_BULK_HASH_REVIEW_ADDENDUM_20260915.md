# ccode review addendum — close the bulk-hash gap before EC2 restoration

Authoritative branch: `chatgpt/frankie-lawful-recovery-clean-20260915`

Run `using-agent-skills` first. Do not launch Frankie, Granite, market data, or a result-bearing cycle.

## Concrete finding

The exact ccode restoration package is now grafted onto the lawful branch by Git object identity. Inspection of its authoritative `RESTORATION_MANIFEST.json` found one known critical gap:

- `E:/Codex/Frankie-BOSS-20260915/source-recovery-resume-20260915/source.sqlite`
- bytes: `11700711424`
- manifest `files[].sha256`: `null`

This is the final Sunday source journal and is result-bearing. Path + byte count is not sufficient for EC2/S3 restoration. Do **not** edit the original manifest; preserve blob `43fba82e294dc881ed72b1a1c46fbe878b215284` unchanged.

## New tools on the clean branch

1. `operations/audit_sunday_restoration_manifest.py`
   - fail-closed audit of all 27 bulk rows;
   - accepts manifest row hashes, independent pinned/secondary hashes, or a separately attested addendum;
   - normalizes Windows slash spelling for comparison only;
   - rejects missing or conflicting hashes;
   - when an addendum is used, binds it to the exact manifest-content SHA and requires two matching full-file hash reads.

2. `operations/build_sunday_bulk_hash_addendum.py`
   - run on the source workstation only;
   - discovers only bulk rows genuinely missing a hash;
   - refuses an existing `-wal`, `-shm`, or `-journal` sidecar;
   - verifies manifest byte count;
   - hashes each missing file twice with independent full reads;
   - refuses size/mtime movement or hash disagreement;
   - writes `FRANKIE_SUNDAY_BULK_HASH_ADDENDUM_V1` without changing the original manifest.

3. Focused tests: `tests/test_sunday_restoration_manifest_audit.py`.

## What to do

First run the audit without an addendum and confirm it fails closed. Verify that the missing set is exactly the expected source SQLite file; if there is anything else, stop and report it.

Then, after independently confirming no source-recovery writer is alive and no SQLite sidecars exist, run the addendum builder against the authoritative manifest. Expect one file to be double-hashed. The 11.7 GB file is intentionally read twice.

Run the audit again with the generated addendum. It must report all 27 bulk files hash-complete with zero missing and zero conflicting hashes.

Commit the generated addendum to your own ccode review branch or return it to Greg/ChatGPT for import. Include its SHA-256 and the exact source branch/commit used to generate it. Do not replace the original manifest.

Also run the focused restoration-audit tests and the native-runtime diagnostic tests from the main ccode handoff.

This hash closure is a launch gate before any S3 upload or EC2 result-bearing restoration.
