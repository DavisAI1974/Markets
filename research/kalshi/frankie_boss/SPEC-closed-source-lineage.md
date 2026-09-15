# Closed-source lineage sidecar

FRANKIE_CLOSED_SOURCE_LINEAGE_V1 is separate from original source receipts. Its ordered links bind exact recovery receipt SHA256 and closed-parent path/physicalSHA/count/head. The newest recovery receipt must match the final ingestion receipt pin; subsequent recovered_path fields must match the previous closed parent. Rewritten entries are refused. Each closed parent's physical bytes and SQLite tail are checked without opening the active/final source database. The host separately verifies each child's historical rehydration-boundary digest after completion.

The operational one-shot watcher waits final ingestion and absence of failure, then emits lineage.json plus a separate outer execution receipt containing lineage path/SHA. The host runtime must receive that independently pinned path/SHA. Older failed forks do not acquire invented ingestion receipts: their original recovery and failure files remain unchanged. A previous receipt's initial rehydration head is never treated as its eventual closed head.

Five new tiny closed-database seams passed: two-generation ancestry with differing initial/final heads, wrong order, changed receipt pin, changed parent bytes, and final failure gate. No actual source replay, old passing tests, or active journal reads were performed.

A sixth independent seam verifies that a rehashed receipt with a false parent count cannot override the actual closed SQLite tail; it passed separately without repeating the first five.
