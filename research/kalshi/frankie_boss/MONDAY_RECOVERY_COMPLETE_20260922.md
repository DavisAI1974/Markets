# Monday ingestion recovery completed — 2026-09-22 ET

Independent verification: https://github.com/DavisAI1974/Markets/actions/runs/35797842849 (success; completion at 2026-09-23T00:05:18Z).
Publication: https://github.com/DavisAI1974/Markets/actions/runs/35797500956 (success).
Conformance computation: run35796793428, implementation01945e24da7ac3e628b897a5d45fda2cde9b1536.

The original ingest remains Cancelled. A separate complete recovery receipt now exists. Full canonical conformance and original-implementation checkpoint roundtrip passed. The compute workflow's old upload transport failed after completion; the independent retained-artifact publisher succeeded. Never replay or recompute because of that old publication failure.

All 2,032,203 retained source records are verified. Exact requested receive-time window Sunday18:00ET–Monday17:00ET contains 2,031,756 records; the first447 are retained pre-open context (244 snapshot and203 other records). Tuesday's19,182 records in the Monday UTC partition were excluded. The Monday partition had1,994,358 records, of which1,975,176 were retained; the earlier UTC partition contributed57,027 including pre-open context.

Original container preserved at /opt/frankie-box/work/ingest-20211004-ingest-1790057801/journal.compact.sqlite; physical SHA256947949d84732b0d7fa22b2e853ee89fdcfaf995955d9de652b36b344333b9888;23,687,368,704bytes.
Recovered checkpoint SHA2560262b0e9b2822086ebb876a437a98821579d64f74a8d4188f3db4b73aeb682b5.
No source replay, adapter.apply, parent writes, model calls or training updates occurred.

AWS canonical artifacts: s3://frankie-granite42-568968024170-us-east-1/readiness/20260922/sealed-recovery/35797500956/
Independent receipt: same bucket, readiness/20260922/sealed-recovery/35797842849/verified-ingestion-recovery.json.
Git JSON files preserve log-emitted integer text without JavaScript numeric conversion. AWS original receipt SHA256 remains authoritative; Git receipt whitespace differs because the publication log flattened newlines.

Next: adapt the schedule preparation gate to the explicit recovery schema without fabricating a legacy ingest receipt; bind the original container in place. Native launch/cycle0 remains unrun.
