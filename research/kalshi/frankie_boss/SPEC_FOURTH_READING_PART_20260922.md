# Fourth reading part preservation — 2026-09-22

Greg confirmed the missing part is reading part4/4. Sections4.2 and4.4 remain for their normal run.

The retained note exists. Its first merge developed runaway repetition; the next refused truncated input; the final merge explicitly discarded part4. This proves a merge failure, not absence of analytical hypotheses. Keep the original records intact.

The current hash-only guard cannot establish complete note preservation: a part can contain no SHA256 at all, or can become attached to an intermediate group whose hashes survive while its text disappears. Strengthen the guard to require every nonblank input line, stripped only at its outside whitespace, to appear exactly as a nonblank output line. Reordering/deduplication is permitted; unprovable paraphrase uses the full original inputs verbatim. Retain every unusable model output separately with existing movement receipts.

A conservative fallback can prevent size reduction. After each fan-out level, if guarded notes do not shrink in total UTF-8 bytes, terminate merging with all guarded notes intact. Never recurse indefinitely or impose a new output limit. Existing physical context admission may refuse oversized notes; it must not truncate them.

Validation: replay the original retained merge outputs through the current guard with docs-index SHA/byte checks; exercise quiet hash-free loss, echo-only headings, mixed intermediate groups, allowed reorder/dedup and no-progress termination. No model call, source replay or production host change for these tests.
