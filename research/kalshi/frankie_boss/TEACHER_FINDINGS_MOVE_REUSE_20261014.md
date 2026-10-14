# Teacher findings reuse after a verified source move

The October 14 saved-day startup reached `Run.teacher_account_entry` in both
the owner and class workers. Both entered `teacher_findings.compute`, repeating
the same 161,126,241,394-byte sidecar pass. Cached findings were complete
(FORMAT=2, 771,787 rows). The source hash still equalled the teacher clean's
full write-stream SHA-256, but the move changed mtime from
1791605071960496456 to 1791676650084198392. The old cache compared size and
mtime only and rejected the retained result. The teacher move also recorded
`claims_work: null` because it searched only root/work/file-claims.jsonl.

The fix keeps the immutable findings and their original source metadata.
A metadata miss can reuse them only when an existing complete-source file
claim matches the recorded hash and byte count and still holds for the actual
resolved file, including inode, size, mtime, filesystem identity and tail hash.
A missing or invalid witness takes the original full computation path.
Publication takes one filesystem lock around the account operation so the
owner and class worker cannot both compute/publish the same output.

The mover now supports a teacher's own file-claims.jsonl and retains the
write-stream claim beside the archived file as well, where consumers resolving
the original symlink can find it. No mathematical computation, row, plane,
clock, formatting rule or scientific output is changed.

Source syntax and diff checks passed. This is a fix identified during the real
saved-day run; the gauge itself did not exercise this metadata-miss path.
Runtime verification and exact continuation status belong in the next saved-day
handoff. The completed publication is copied aside before any replay recovery.
