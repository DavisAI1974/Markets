# Linux trading-day preparation adapter — 2026-09-23

Objective: run the existing prepare_trading_day operation against the independently verified Monday recovery on its Linux box, preserving the original sealed journal in place. This is data preparation and archival only. Cycle 0 remains held.

Assumptions and scope: the caller supplies the reviewed clean checkout and a complete, hash-pinned configuration already staged through the established S3 helper route. No context rows, cutoff rule, roster, host path, or forecast anchor is inferred. This adapter does not create or change schedule semantics, relocate host configuration, install dependencies, or start any runtime.

Files: deploy/aws/box/frankie_box_prepare_trading_day.py and research/kalshi/frankie_boss/tests/test_box_trading_day_preparation.py. Existing source, host, digest, bootstrap and workflows remain unchanged.

Commands:
- Prepare: python -B deploy/aws/box/frankie_box_prepare_trading_day.py prepare --configuration ABSOLUTE_FILE --configuration-sha256 SHA256 --commit FULL_COMMIT --output-root /opt/frankie-box/work/trading-day-preparation/UNIQUE_RUN
- Publish separately after signing the returned archive/receipt hashes: python -B deploy/aws/box/frankie_box_prepare_trading_day.py publish --output-root SAME_ROOT --upload-map PRIVATE_MAP --upload-map-sha256 SHA256
- Test in isolated remote Linux CI: python -m pytest -q research/kalshi/frankie_boss/tests/test_box_trading_day_preparation.py

Behavior:
1. Require Linux, exact clean tracked code at the explicit commit, input byte hash, absolute paths without symlink ancestors, and no literal credentials in configuration.
2. Before any output write, require every launch field, a nonempty pinned cutoff roster, explicit verified-recovery descriptor, exact original container path/bytes/hash, and fresh output root. The existing preparation function remains the authority for complete recovery and scientific validation.
3. Output paths must be exactly ROOT/schedule, ROOT/prefixes, ROOT/prepared-configuration.json. Write and fsync preparation-intent.json before invoking the existing operation. Preserve partial output and intent on any failure; never retry preparation into an existing root.
4. Archive only generated schedule, prefix and prepared-configuration files plus the intent and preparation receipt. Reject symlinks, nonregular files and hard links. Never archive the original 23 GB container or input credentials. Include file byte/SHA witnesses; keep exact integer JSON processing in Python. Source inode/size/mtime are checked after preparation as an additional mutation guard.
5. Publication is independently retryable to a fresh explicit S3 prefix, without rerunning preparation. Its private URL map binds the two local file hashes and keys under readiness/20260922/trading-day-preparation/UNIQUE_RUN in the established private bucket. Presigned PUTs must sign If-None-Match and x-amz-checksum-sha256. Stream the archive, upload the publication receipt last, and never overwrite/delete S3 evidence. An upload failure is not a successful publication. No URL/credential is printed.
6. Preparation produces a reviewable archive, not a native-host deployment. Prepared paths continue to describe the original Linux evidence; native-host delivery/admission still needs its separately reviewed coherent bindings.

Verification: real tiny recovered-journal fixture proves preparation does not mutate source and preserves exact timestamp integers. Negative tests cover null launch fields, wrong config bytes, copied source pin, existing outputs, path escape/symlinks, code mismatch and credential presence. Publication tests fake only the network boundary and prove ordering, checksum bindings, no overwrite headers and failure behavior.

Plan/tasks: first land this spec and the tests for a failing remote CI result; then add the adapter; root reviews and runs focused CI. Only root integrates commits/refs and authors an execution workflow once actual configuration and all launch gates are satisfied.
