# Build notes: the graph while a run goes (live.py, signal_packet.py)

2026-11-24 piece 1 done: tools/kgraph/live.py follow. Check on 0f33fec4 (90 commits): 23 s, equal to one ingest_platform load,
only the run's events.jsonl Source node has more than one revision (90, its commit and bytes change). NEXT: ea4c check, signal_packet.py, tests.

2026-11-24 run 81: piece 1 second check done. Follower on ea4c1d2e (143 commits) push by push: 39.8 s, ends with the same
(node id, content_sha) and (edge id, content_sha) as one ingest_platform load of the finished run; a second follow writes nothing.
0f33fec4 (90 commits): 25.3 s, same. Piece 2 done: tools/kgraph/signal_packet.py (build, leakage_check, --all-opens).
On 0f33fec4 at 6000 tokens: first opening (seq 1) 612 tokens, middle (seq 1299) 5951, last (seq 2951) 5930; over all 217
the smallest is seq 1 (612), the largest seq 105 (5998); 0 breaches on all 217.
Found in run 77's files: the check of a later row used a row whose receive time equalled the signal's, so "after the
moment" could not show; the signal line left out the journaled `conditions`; the per-store cache keyed on id() alone.
All three fixed. Not done: no packet section for claims (all out on the 2023 tape), none for peaks.
