# Prior loose files preserved in Git

The original relocation receipt moved prior analysis files off C:, but left 13 existing compressed bulk archives and seven bytecode files outside Git. This preservation set retains **all 4,922,716,488 bytes**, without extraction, recompression or discarding any source content. All 20 files are listed in `index.json`, with individual manifests and ordered binary parts no larger than 64 MiB.

For each file, concatenating its manifest's parts in listed offset order yields the exact original file bytes. Each part has its own byte count and SHA-256. These are transport/preservation checks on the new parts, not a new frozen database or dataset scan. The source archives are never opened as databases or decoded as research data during this move.

Files are pushed in bounded batches. The original loose files are retained until all parts, manifests and index are reachable at the requested GitHub branch, and every part's Git blob identity and ordered bytes have been checked against its loose original. `verified-deletion-candidates.json` records that checkpoint; `local-cleanup-receipt.json` records the subsequent removal of only those byte-verified redundant loose copies. The full supporting data remain in Git. Original AWS S3 archives, EBS volumes, attempts and snapshot are untouched.

Use `tasks/family-research-20261022/preserve_prior_local_files.py` for the recorded preservation procedure. Current lifecycle analysis uses already materialized source files in Git and does not need to recreate these loose archives. Older helpers naming the former loose archive paths need to read the ordered parts as one byte stream; do not repeat setup or a broad source restoration just to continue analysis.

No original C: file listed in the prior relocation receipt remained when checked in this continuation. That statement is scoped to the receipt's 344 recorded paths, not an unrestricted scan of the user's computer. New artifacts are saved only inside `E:/Markets-family-research-handoff` and committed to Git.
